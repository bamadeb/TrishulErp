"""Master codes the trip logic depends on. They are rows in trk.trip_status (is_system = 1), so they
exist in every database; everything else about a status is data."""

IN_PROGRESS = "In progress"
COMPLETED = "Completed"
AUTO_CLOSED = "Auto closed"
