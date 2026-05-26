from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone


class Expedition(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        EN_COURS = "EN_COURS", "En cours"
        LIVREE = "LIVREE", "Livrée"
        ANNULEE = "ANNULEE", "Annulée"

    # Référence auto
    reference = models.CharField(max_length=30, unique=True, blank=True, editable=False)
    annee = models.PositiveSmallIntegerField(default=2026, editable=False, db_index=True)
    numero = models.PositiveIntegerField(default=0, editable=False, db_index=True)

    client_nom = models.CharField(max_length=120, default="Client inconnu")
    client_email = models.EmailField(default="client@transport.com")

    origine = models.CharField(max_length=200, default="Origine inconnue")
    destination = models.CharField(max_length=200, default="Destination inconnue")

    poids_kg = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    description = models.TextField(blank=True, default="")

    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.EN_ATTENTE,
        db_index=True,
    )

    date_creation = models.DateTimeField(auto_now_add=True)
    date_maj = models.DateTimeField(auto_now=True)
    date_cible = models.DateField(null=True, blank=True, db_index=True)

    class TypeColis(models.TextChoices):
        DOCUMENTS = "DOCUMENTS", "Documents"
        COLIS = "COLIS", "Colis"
        FRAGILE = "FRAGILE", "Fragile"
        ALIMENTAIRE = "ALIMENTAIRE", "Alimentaire"
        AUTRE = "AUTRE", "Autre"

    client_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="expeditions"
    )

    pickup_adresse = models.CharField(max_length=255, blank=True, default="")
    dropoff_adresse = models.CharField(max_length=255, blank=True, default="")

    type_colis = models.CharField(
        max_length=20,
        choices=TypeColis.choices,
        default=TypeColis.COLIS,
        db_index=True,
    )

    instructions = models.TextField(blank=True, default="")

    # Livraison programmée : si null => immédiate
    planifiee_pour = models.DateTimeField(null=True, blank=True, db_index=True)

    # Annulation
    raison_annulation = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-date_creation"]
        indexes = [
            models.Index(fields=["annee", "numero"]),
        ]

    def __str__(self) -> str:
        return f"{self.reference} ({self.get_statut_display()})"

    def clean(self):
        super().clean()
        errors = {}

        if self.poids_kg is not None and self.poids_kg < 0:
            errors["poids_kg"] = "Le poids doit être positif ou nul."

        if self.date_cible and self.date_cible < timezone.localdate():
            # Tolérance : on bloque uniquement à la création.
            if not self.pk:
                errors["date_cible"] = "La date cible ne peut pas être dans le passé."

        if self.planifiee_pour and self.planifiee_pour < timezone.now():
            if not self.pk:
                errors["planifiee_pour"] = "La date de planification doit être dans le futur."

        if self.origine and self.destination and self.origine.strip().lower() == self.destination.strip().lower():
            errors["destination"] = "La destination doit être différente de l'origine."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Génère la référence uniquement à la création
        if not self.pk and not self.reference:
            year = timezone.now().year
            self.annee = year

            with transaction.atomic():
                last = (
                    Expedition.objects
                    .filter(annee=year)
                    .order_by("-numero")
                    .first()
                )
                next_num = (last.numero if last else 0) + 1
                self.numero = next_num
                self.reference = f"EXP-{year}-{next_num:04d}"

        return super().save(*args, **kwargs)


class Vehicule(models.Model):
    class Statut(models.TextChoices):
        DISPONIBLE = "DISPONIBLE", "Disponible"
        EN_MISSION = "EN_MISSION", "En mission"
        MAINTENANCE = "MAINTENANCE", "Maintenance"

    immatriculation = models.CharField(max_length=20, unique=True)
    marque = models.CharField(max_length=50, blank=True, default="")
    modele = models.CharField(max_length=50, blank=True, default="")
    capacite_kg = models.PositiveIntegerField(default=1000)
    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.DISPONIBLE,
        db_index=True,
    )

    def __str__(self):
        return f"{self.immatriculation} ({self.get_statut_display()})"


class Livraison(models.Model):
    class Statut(models.TextChoices):
        PLANIFIEE = "PLANIFIEE", "Planifiée"
        EN_COURS = "EN_COURS", "En cours"
        TERMINEE = "TERMINEE", "Terminée"
        ANNULEE = "ANNULEE", "Annulée"

    expedition = models.OneToOneField(Expedition, on_delete=models.CASCADE, related_name="livraison")
    vehicule = models.ForeignKey(Vehicule, on_delete=models.PROTECT, related_name="livraisons")

    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.PLANIFIEE, db_index=True)
    date_depart = models.DateTimeField(null=True, blank=True)
    date_arrivee = models.DateTimeField(null=True, blank=True)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    position_maj = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]

    def save(self, *args, **kwargs):
        # Si une position est définie, on horodate automatiquement la dernière mise à jour.
        if self.lat is not None and self.lng is not None:
            self.position_maj = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Livraison {self.expedition.reference} - {self.vehicule.immatriculation}"


class TrackingEvent(models.Model):
    expedition = models.ForeignKey(
        Expedition,
        on_delete=models.CASCADE,
        related_name="events"
    )
    statut = models.CharField(
        max_length=20,
        choices=Expedition.Statut.choices
    )
    commentaire = models.TextField(blank=True)
    date_event = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_event"]

    def __str__(self):
        return f"{self.expedition.reference} - {self.get_statut_display()}"