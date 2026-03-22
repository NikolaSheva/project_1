from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from watch.services.exchange import get_usd_rate


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Название бренда")
    slug = models.SlugField(max_length=100, unique=True, blank=True)

    class Meta:
        verbose_name = "Бренд часов"
        verbose_name_plural = "Бренды часов"
        # ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class City(models.Model):
    name = models.CharField(max_length=50, unique=True)
    # slug = models.SlugField(max_length=60, unique=True, blank=True)

    class Meta:
        verbose_name = "Город"
        verbose_name_plural = "Города"
        # ordering = ['name']

    def __str__(self):
        return self.name

    # def save(self, *args, **kwargs):
    #     if not self.slug:
    #         self.slug = slugify(self.name)
    #     super().save(*args, **kwargs)


class Product(models.Model):
    def get_price_rub(self):
        if self.price_usd is not None:
            return round(self.price_usd * get_usd_rate())
        return None

    # Связи
    brand = models.ForeignKey(
        Brand, on_delete=models.CASCADE, related_name="products", verbose_name="Бренд"
    )
    cities = models.ManyToManyField(City, related_name="products", blank=True)

    # Основная информация
    title = models.CharField(max_length=255, verbose_name="Название")
    slug = models.SlugField(max_length=255, blank=True)
    url = models.URLField(unique=True, verbose_name="URL товара")

    model = models.CharField(max_length=100, blank=True, null=True, verbose_name="Модель")
    ref = models.CharField(max_length=100, blank=True, null=True, verbose_name="Референс")
    
    # Цены
    price_usd = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name="Цена (USD)",
    )
    price_text = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Цена (текст)",
        help_text="Например: 'По запросу', 'Договорная' и т.д."
    )
    
    # Характеристики
    collection = models.CharField(max_length=100, blank=True, null=True, verbose_name="Коллекция")
    case_material = models.CharField(max_length=100, blank=True, null=True, verbose_name="Материал корпуса")
    water_resistance = models.CharField(max_length=50, blank=True, null=True, verbose_name="Водонепроницаемость")
    case_diameter = models.CharField(max_length=50, blank=True, null=True, verbose_name="Диаметр корпуса")
    dial_color = models.CharField(max_length=100, blank=True, null=True, verbose_name="Цвет циферблата")
    bezel = models.CharField(max_length=100, blank=True, null=True, verbose_name="Безель")
    movement_type = models.CharField(max_length=100, blank=True, null=True, verbose_name="Тип механизма")
    functions = models.TextField(blank=True, null=True, verbose_name="Функции")
    power_reserve = models.CharField(max_length=50, blank=True, null=True, verbose_name="Запас хода")
    caliber = models.CharField(max_length=50, blank=True, null=True, verbose_name="Калибр")
    strap_material = models.CharField(max_length=100, blank=True, null=True, verbose_name="Материал ремешка")
    комплектация = models.TextField(blank=True, null=True, verbose_name="Комплектация")
    condition_detail = models.CharField(max_length=200, blank=True, null=True, verbose_name="Состояние (детально)")
    glass = models.CharField(max_length=100, blank=True, null=True, verbose_name="Стекло")
    
    # Визуальная информация
    image_url = models.URLField(blank=True, null=True, verbose_name="URL изображения")

    # Даты
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    telegram_sent_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="Отправлено в Telegram"
    )

    class Meta:
        indexes = [
            models.Index(fields=["title"]),
        ]

    def __str__(self):
        return f"{self.brand.name} {self.title}"

    def get_absolute_url(self):
        return reverse("product_detail", kwargs={"slug": self.slug})

    class Meta:
        indexes = [
            models.Index(fields=["title"]),  # Добавлен индекс для поиска по названию
        ]

    def __str__(self):
        return f"{self.brand.name} {self.title}"

    def get_absolute_url(self):
        return reverse("product_detail", kwargs={"slug": self.slug})


class FilterPreset(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название фильтра")

    # Условия фильтрации
    brand = models.ManyToManyField(
        Brand,
        blank=True,
        related_name="filter_presets",  # Добавлено
        verbose_name="Бренды",
    )

    in_stock = models.ManyToManyField(
        City,
        blank=True,
        related_name="filter_presets",  # Добавлено
        verbose_name="Наличие в городах",
    )

    # condition = models.CharField(
    #     max_length=20,
    #     choices=Product.CONDITION_CHOICES,
    #     blank=True,
    #     null=True,
    #     verbose_name="Состояние"
    # )

    # special_offers_only = models.BooleanField(
    #     default=False,
    #     verbose_name="Только спецпредложения"
    # )

    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    is_active = models.BooleanField(default=True, verbose_name="Активный фильтр")

    class Meta:
        ordering = ["-created_at"]  # Сортировка по дате создания

    def __str__(self):
        return self.name

class ProductImage(models.Model):
    """Модель для хранения нескольких фото товара"""
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='additional_images',
        verbose_name="Товар"
    )
    image_url = models.URLField(verbose_name="URL изображения")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок")
    
    class Meta:
        ordering = ['order']
        verbose_name = "Дополнительное фото"
        verbose_name_plural = "Дополнительные фото"
        indexes = [
            models.Index(fields=['product']),  # Добавьте эту строку
        ]
    
    def __str__(self):
        return f"Фото для {self.product.title} ({self.order})"