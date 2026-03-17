import time
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from transport.models import Expedition

# Mini trajet : Paris (Tour Eiffel) -> Paris (Notre-Dame) -> Paris (Bastille)
ROUTE = [
    (48.858370, 2.294481),
    (48.860600, 2.337600),
    (48.852968, 2.349902),
    (48.853000, 2.370000),
]


def interpolate(a, b, steps: int):
    """Génère des points intermédiaires entre 2 coordonnées."""
    (lat1, lng1) = a
    (lat2, lng2) = b
    for i in range(steps):
        t = (i + 1) / steps
        yield (lat1 + (lat2 - lat1) * t, lng1 + (lng2 - lng1) * t)


class Command(BaseCommand):
    help = "Simule le déplacement GPS d'une livraison pour une expédition donnée."

    def add_arguments(self, parser):
        parser.add_argument("reference", type=str, help="Référence expédition (ex: EXP-2026-0001)")
        parser.add_argument("--steps", type=int, default=25, help="Points intermédiaires entre 2 étapes")
        parser.add_argument("--sleep", type=float, default=2.0, help="Pause en secondes entre updates")
        parser.add_argument("--loop", action="store_true", help="Boucle infinie")

    def handle(self, *args, **options):
        reference = options["reference"]
        steps = options["steps"]
        sleep_s = options["sleep"]
        loop = options["loop"]

        try:
            exp = Expedition.objects.get(reference=reference)
        except Expedition.DoesNotExist:
            raise CommandError(f"Expedition introuvable: {reference}")

        if not hasattr(exp, "livraison"):
            raise CommandError("Cette expédition n'a pas de livraison. Planifie-la d'abord (planifier-livraison).")

        liv = exp.livraison

        def run_once():
            points = []
            for i in range(len(ROUTE) - 1):
                points.append(ROUTE[i])
                points.extend(list(interpolate(ROUTE[i], ROUTE[i + 1], steps)))
            points.append(ROUTE[-1])

            self.stdout.write(self.style.SUCCESS(f"Simulation démarrée pour {reference} ({len(points)} points)."))
            for (lat, lng) in points:
                liv.lat = lat
                liv.lng = lng
                # position_maj sera auto via ton save(), mais on la met aussi pour clarté
                liv.position_maj = timezone.now()
                liv.save(update_fields=["lat", "lng", "position_maj"])

                self.stdout.write(f" -> {lat:.6f}, {lng:.6f}")
                time.sleep(sleep_s)

            self.stdout.write(self.style.SUCCESS("Simulation terminée."))

        if loop:
            while True:
                run_once()
        else:
            run_once()