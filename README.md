# ideal-octo-spork
A simple reservation system backend

Naming is a WIP. The product team declined to provide an official spelling, so now it's whatever github autogenerated.

## qr.py
Combined schema, ORM, and server route definitions.

Run with 
```fastapi dev qr.py```

fastapi also puts auto generated API docs and an API tester at /docs.

All state is stored in a sqlite file called app.db

The current flow assumes there's a totally separate frontend server out there
that serves a web client people use. The api exposed here stays hidden. The
steps to that flow are linear:

### User wants to open an event ("spot") for reservations

1. User uses client (not this program) to fill out what start/end times ("slots") they want to offer and how many tickets will be available for each. Importantly, the user must give their spot a name. Client hits the /make_spot endpoint here with a CSpot json object.

2. Client uses the spot name the user gave it to display a QR code embedding a frontend URL that contains the spot_name.

### Other users want a ticket for a spot

3. Other user follows URL from the QR in (2) to get the client. Client uses the spot_name embedded in the URL to hit /reserve/{spot_name} here. This returns a CTicket json object.

4. Other user's client uses the CTicket from (4) to display a QR that contains json for the CTicket

### Optionally, a ticket checker wants to validate tickets

5. Ticket checker gets a client from somewhere not here

6. That client scans the QR from (4) to hit the /redeem/{spot_id}/{ticket_id} endpoint here, which returns the number of times that ticket has been previously presented. (Might be useful in the future to return the time of of the last presentment too, in case of accidental multiple scannings)

### Comments

Strictly speaking, we don't _need_ to have a separate frontend. Some simple static pages could get served from here and new endpoints could be made to accommodate not having a frontend.

