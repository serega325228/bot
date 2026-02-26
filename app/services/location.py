from geopy.distance import geodesic

from app.settings import settings
from app.models.stop import Stop

class LocationService:
    def _distance_meters(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        return geodesic((lat1, lon1), (lat2, lon2)).meters

    async def find_stop_in_radius(
        self,
        *,
        latitude: float,
        longitude: float,
        stop: Stop
    ) -> Stop | None:
        dist = self._distance_meters(
            latitude,
            longitude,
            stop.latitude,
            stop.longitude,
        )
        
        if dist <= settings.STOP_RADIUS_METERS:
            return stop

        return None




