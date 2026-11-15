# Visit Billing System

An event-driven application built with FastAPI, PostgreSQL, and
RabbitMQ.

Users can create and complete visits. Completing a visit triggers an
asynchronous billing workflow. The project is structured as a modular
monolith: the Visits and Billing modules own their own data and
communicate through events rather than accessing each other's tables.

## Run with Docker

### Requirements

-   Docker
-   Docker Compose

### 1. Configure the environment

Copy the Docker environment example:

``` bash
cp .env.docker.example .env.docker
```

The file contains the connection settings used by containers. Notice
that `db` and `rabbitmq` are Docker Compose service names; `localhost`
would not point to those containers.

### 2. Build and start the services

``` bash
docker compose up -d --build
```

This starts:

-   FastAPI application
-   Outbox publisher
-   Billing consumer
-   PostgreSQL
-   RabbitMQ

The API and background processes use the same application image but run
as separate containers.

### 3. Apply database migrations

``` bash
docker compose run --rm api alembic upgrade head
```

### 4. Open the application

-   API: http://localhost:8000
-   Interactive API documentation: http://localhost:8000/docs
-   RabbitMQ management UI: http://localhost:15672
    -   Username: `app`
    -   Password: `app`

### Useful Docker commands

View service status:

``` bash
docker compose ps
```

View logs:

``` bash
docker compose logs -f api outbox-worker billing-consumer
```

Stop the services:

``` bash
docker compose down
```

Stop the services and remove the persisted database and RabbitMQ data:

``` bash
docker compose down -v
```

The last command deletes the named volumes and their data.

## Complete Workflow

### 1. Create a visit

Send a request:

`POST /api/visits`

Example payload:

``` json
{
  "start_date_time": "2026-11-16T10:00:00+00:00",
  "end_date_time": "2026-11-16T11:30:00+00:00",
  "description": "Consultation",
  "rate": "80.00"
}
```

The API creates a visit with the `Scheduled` status and returns its ID.

### 2. Complete the visit

Send a request using the returned ID:

`POST /api/visits/{visit_id}/complete`

The Visits module locks the visit row, validates its current status,
changes it to `Completed`, and inserts a `VisitCompleted` event into the
Outbox table.

The visit update and Outbox insert are committed in the same database
transaction. This means the event cannot be lost between updating the
visit and recording the intention to publish it.

### 3. Publish the event

The Outbox worker periodically looks for unpublished events. It
publishes each event to RabbitMQ and marks it as published after
receiving broker confirmation.

If publishing fails, the event remains unpublished and is retried in a
later polling cycle.

### 4. Process the event and create billing

The Billing consumer receives the `VisitCompleted` event. It validates
the payload, checks whether the event has already been processed,
calculates the amount from the rate and visit duration, and creates a
billing record.

The billing record and processed-event entry are saved in one database
transaction. Duplicate deliveries are ignored, preventing the same event
from creating another billing record.

### 5. Result

For the example above:

-   Visit status: `Completed`
-   Duration: 1.5 hours
-   Hourly rate: `$80.00`
-   Billing amount: `$120.00`
-   Billing status: `Created`

Billing is asynchronous, so the visit may be marked as completed before
its billing record is available. If RabbitMQ is temporarily unavailable,
the Outbox keeps the event for retry.

## Running Tests

Create test database:

``` bash
docker compose exec db createdb -U app visit_billing_test
```

If the database already exists, you can skip this step.

Run the test suite:

``` bash
docker compose run --rm api python -m pytest -v
```
