"""
Basic reservation system backend. Structured into definitions for client-facing
serializable objects, ORM objects, and endpoint logic.
"""
import pydantic
from typing import List,Optional, Tuple
import numpy as np
import peewee
import uuid
import time
from mmh3 import mmh3_x64_128_digest
from fastapi import FastAPI

db = peewee.SqliteDatabase('app.db')
app = FastAPI()

################################################################################
################################################################################
################################################################################

def make_id(model:pydantic.BaseModel):
    R = np.frombuffer(uuid.uuid4().bytes,dtype=np.int64)
    H = np.frombuffer(
        mmh3_x64_128_digest(model.json().encode('utf8')),dtype=np.int64
    )
    return int(R[0] ^ R[1] ^ H[0] ^ H[1])

###

# Dataclass-like definitions for objects meant to go to and from a 
# client facing frontend server.

class CUnixTime(pydantic.BaseModel,frozen=True):
    """
    Super pedantic and slightly annoying way of notating that a time object is
    actually integer unix seconds without breaking json encoders or decoders.
    """
    seconds:int

class CSlot(pydantic.BaseModel,frozen=True):
    """
    Client facing class representing a reservable interval of time at a specific
    Spot.
    """
    start:CUnixTime
    end:Optional[CUnixTime]
    capacity:Optional[int]=pydantic.Field((1<<13),ge=0,le=(1<<13))
    note:Optional[str]=None

class CSpot(pydantic.BaseModel,frozen=True):
    """
    Client facing class representing an event or venue or location. The values
    of the fields originate from the client, when a user who controls a spot or
    venue or event defines what reservations to offer.
    """
    name:str
    note:Optional[str]=None
    slots:Tuple[CSlot,...]

class CTicket(pydantic.BaseModel,frozen=True):
    """
    A reservation/ticket class composed by the backend and given to the
    frontend. The ordered tuple (spot_id,ticket_id) is guaranteed to be unique.
    """
    slot:CSlot
    spot_name:str
    spot_id:int
    ticket_id:int
    note:Optional[str]=None
    
################################################################################
################################################################################
################################################################################

# ORM Models for controlling the sqlite db through peewee. Classes here are
# backend facing only, and have extra fields compared to their client facing
# counterparts.
 
class PBaseModel(peewee.Model):
    class Meta:
        database = db

class PSpot(PBaseModel):
    id = peewee.IntegerField(unique=True,index=True)
    name = peewee.CharField(primary_key=True)
    note = peewee.TextField(null=True)

class PSlot(PBaseModel):
    id = peewee.IntegerField(primary_key=True)
    spot_id = peewee.IntegerField(index=True)
    start = peewee.IntegerField(index=True)
    end = peewee.IntegerField(null=True)
    capacity = peewee.IntegerField() # max number of tickets to allow issuing
    note = peewee.TextField(null=True)
    reservations = peewee.IntegerField() # number of tickets issued

class PTicket(PBaseModel):
    ticket_id = peewee.IntegerField(primary_key=True)
    slot_id = peewee.IntegerField(index=True)
    spot_id = peewee.IntegerField(index=True)
    presentments = peewee.IntegerField()
    note = peewee.TextField(null=True)
    serial_number = peewee.IntegerField()

db.create_tables(PBaseModel.__subclasses__())

################################################################################
################################################################################
################################################################################

# Server operations

def make_slot(cslot,spot_id):
    PSlot.create(
        id=make_id(cslot),
        spot_id=spot_id,
        start=cslot.start.seconds,
        end=cslot.end.seconds if cslot.end else None,
        capacity = cslot.capacity,
        note = cslot.note,
        reservations=0
    )

@app.post('/make_spot')
@db.atomic()
def make_spot(cspot:CSpot):
    spot_id = make_id(cspot)
    PSpot.create(
        name=cspot.name,
        id=spot_id,
        note=cspot.note
    )
    for cslot in cspot.slots:
        make_slot(cslot,spot_id)

def get_available(spot_id,now=None):

    if now is None:
        now = int(time.time())

    available=(PSlot.select()
        .where(
            (PSlot.reservations <= PSlot.capacity) &\
            (PSlot.spot_id == spot_id ) &\
            (PSlot.start >= now)
        )
        .order_by(PSlot.start)
    )

    return list(available)

def get_spot_id(spot_name):
    spots = PSpot.select().where(PSpot.name == spot_name)
    spots=list(spots)
    if len(spots) != 1:
        raise Exception(
            f'spot name {spot_name} associated with {len(spots)} IDs'
        )
    return spots[0].id

@app.post('/reserve/{spot_name}')
@db.atomic()
def reserve_ticket(spot_name:str,note:str=None)->CTicket:

    spot_id = get_spot_id(spot_name)
    available = get_available(spot_id)

    if len(available) == 0:
        return None
    
    pslot = available[0]

    ticket_id = np.frombuffer(uuid.uuid4().bytes,dtype=np.int64)
    ticket_id = int(ticket_id[0]^ticket_id[1])

    PTicket.create(
        ticket_id=ticket_id,
        slot_id=pslot.id,
        spot_id=spot_id,
        presentments=0,
        note=note,
        serial_number=pslot.reservations
    )

    cticket = CTicket(
        slot=CSlot(
            start=CUnixTime(seconds=pslot.start),
            end=CUnixTime(seconds=pslot.end) if pslot.end else None,
            note=pslot.note
        ),
        spot_name=spot_name,
        spot_id=spot_id,
        ticket_id=ticket_id,
        note=note
    )

    pslot.reservations += 1
    pslot.save()

    return cticket

@app.post('/redeem/{spot_id}/{ticket_id}')
@db.atomic()
def redeem_ticket(spot_id:int,ticket_id:int)->int:
    try:
        pticket = list(
            PTicket
                .select()
                .where(
                    (PTicket.ticket_id==ticket_id) &\
                    (PTicket.spot_id==spot_id)
                )
        )[0]
    except:
        raise Exception(f'No ticket issuance found for {ticket_id}')
    
    presentments = int(pticket.presentments)
    pticket.presentments += 1
    pticket.save()
    
    return presentments