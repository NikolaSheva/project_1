from django.db import models
from django.utils.text import slugify
from django.urls import reverse
from django.core.validators import RegexValidator
from django.core.validators import MinValueValidator
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
    # CONDITION_CHOICES = [
    #     ('new', 'Абсолютно новое'),
    #     ('refurb', 'Изделие "с пробегом"')
    # ]
    #
    # SPECIAL_OFFER_CHOICES = [
    #     ("G", "Grand комплектация"),
    #     ("L", "Limited editions"),
    #     ("S", "Special editions"),
    #     ("A", "Акция"),
    #     ("N", "Новинка"),
    #     ("T", "Тюнинг"),
    # ]


    # Связи
    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name="Бренд"
    )
    cities = models.ManyToManyField(City, related_name="products", blank=True)


    # Основная информация
    title = models.CharField(max_length=255, verbose_name="Название")
    slug = models.SlugField(max_length=255, blank=True)
    url = models.URLField(unique=True, verbose_name="URL товара")

    # Визуальная информация
    image_url = models.URLField(blank=True, null=True, verbose_name="URL изображения")

    # Даты
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    # Характеристики
    # condition = models.CharField(
    #     max_length=20,
    #     choices=CONDITION_CHOICES,
    #     default='new',
    #     blank=False,
    #     db_index=True,  # Добавлено
    #     verbose_name="Состояние"
    # )

    # price = models.CharField(
    #     max_length=100,
    #     null=True,
    #     blank=True,
    #     verbose_name="Цена",
    #     editable=False
    # )
    price_usd = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name="Цена (USD)"
    )

    # special_offer = models.CharField(
    #     max_length=2,
    #     choices=SPECIAL_OFFER_CHOICES,
    #     default='',
    #     blank=True,
    #     db_index=True,  # Добавлено
    #     verbose_name="Спецпредложение"
    # )

    class Meta:
        indexes = [
            models.Index(fields=['title']),  # Добавлен индекс для поиска по названию
        ]

    def __str__(self):
        return f"{self.brand.name} {self.title}"

    def get_absolute_url(self):
        return reverse('product_detail', kwargs={'slug': self.slug})

class FilterPreset(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name="Название фильтра"
    )

    # Условия фильтрации
    brand = models.ManyToManyField(
        Brand,
        blank=True,
        related_name='filter_presets',  # Добавлено
        verbose_name="Бренды"
    )

    in_stock = models.ManyToManyField(
        City,
        blank=True,
        related_name='filter_presets',  # Добавлено
        verbose_name="Наличие в городах"
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
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Активный фильтр"
    )

    class Meta:
        ordering = ['-created_at']  # Сортировка по дате создания

    def __str__(self):
        return self.name