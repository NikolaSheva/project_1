from django import forms
from .models import Brand, City, Product

class ProductFilterForm(forms.Form):
    cities = forms.ModelMultipleChoiceField(
        queryset=City.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Наличие в городах"
    )
    brand = forms.ModelMultipleChoiceField(
        queryset=Brand.objects.all().order_by('name'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Бренды"
    )
    # condition = forms.MultipleChoiceField(
    #     choices=Product.CONDITION_CHOICES,
    #     widget=forms.CheckboxSelectMultiple,
    #     required=False,
    #     label="Состояние"
    # )
    # special_offer = forms.MultipleChoiceField(
    #     choices=Product.SPECIAL_OFFER_CHOICES,
    #     widget=forms.CheckboxSelectMultiple,
    #     required=False,
    #     label="Спецпредложение"
    #)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Оптимизация queryset для уменьшения запросов к БД
        self.fields['cities'].queryset = City.objects.all().only('id', 'name')
        self.fields['brand'].queryset = Brand.objects.all().only('id', 'name')



