import logging
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from watch.models import Brand

logger = logging.getLogger(__name__)

WATCHES = [
    "Неизвестно",
    "AET REMOULD",
    "Alain Silberstein",
    "A. Lange & Sohne",
    "Antoine Preziuso",
    "Arnold & Son",
    "ARTYA",
    "Audemars Piguet",
    "BADOLLET",
    "Bell & Ross",
    "Blancpain",
    "BLU",
    "Breguet",
    "Breitling",
    "Bvlgari",
    "Carl F.Bucherer",
    "Cartier",
    "CHAUMET",
    "Chopard",
    "Christophe Claret",
    "Chronoswiss",
    "Clerk",
    "Corum",
    "Cvstos",
    "Czapek",
    "Daniel Roth",
    "De Bethune",
    "De grisogono",
    "Delaneau",
    "De Witt",
    "EDOUARD KOEHN",
    "FP Journe",
    "Franck Muller",
    "Franc Vila",
    "Frédéric Jouvenot",
    "Frederique Constant",
    "Gerald Charles",
    "Gerald Genta",
    "Girard Perregaux",
    "Glashutte Original",
    "GRAFF",
    "Graham",
    "Greubel Forsey",
    "Harry Winston",
    "HD 3",
    "H. Moser & Cie",
    "Hublot",
    "Ice Link",
    "IWC",
    "Jacob & Co",
    "Jaeger LeCoultre",
    "Jaquet Droz",
    "Jean Dunand",
    "JeanRichard",
    "Jorg Hysek",
    "Laurent Ferrier",
    "L'epee",
    "Longines",
    "Louis Moinet",
    "Maikou Bode",
    "Maurice Lacroix",
    "MB&F",
    "Nivrel",
    "Omega",
    "Panerai",
    "Parmigiani Fleurier",
    "Patek Philippe",
    "Perrelet",
    "Piaget",
    "Pierre Kunz",
    "Quinting",
    "RAFFAEL PAPIAN",
    "Ressence",
    "Richard Mille",
    "Roger Dubuis",
    "Rolex",
    "Romain Jerome",
    "Tag Heuer",
    "THOMAS PRESCHER",
    "Tiffany & Co",
    "Tudor",
    "Ulysse Nardin",
    "Urwerk",
    "Vacheron Constantin",
    "Van Cleef & Arpels",
    "Wyler",
    "Zenith"
]

class Command(BaseCommand):
    help = 'Добавляет предопределенные бренды часов в базу данных'

    def handle(self, *args, **options):
        logger.info("Начало добавления брендов...")
        added, exists = 0, 0

        for name in WATCHES:
            slug = slugify(name)
            brand, created = Brand.objects.get_or_create(
                slug=slug,
                defaults={'name': name}
            )
            if created:
                added += 1
                logger.debug(f"Добавлен бренд: {name}")
            else:
                exists += 1

        logger.info(f"Итог: Добавлено {added}, существовало {exists}")
        self.stdout.write(self.style.SUCCESS('Сидирование брендов завершено!'))


