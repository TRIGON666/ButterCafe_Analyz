from django import forms

from .models import Order


class OrderCreateForm(forms.Form):
    name = forms.CharField(max_length=100, strip=True, error_messages={'required': 'Укажите имя.'})
    phone = forms.CharField(max_length=30, strip=True, error_messages={'required': 'Укажите телефон.'})
    email = forms.EmailField(required=False)
    address = forms.CharField(max_length=255, required=False, strip=True)
    delivery_type = forms.ChoiceField(choices=Order.DELIVERY_CHOICES)
    need_cutlery = forms.BooleanField(required=False)
    need_call = forms.BooleanField(required=False)
    comment = forms.CharField(required=False, strip=True, widget=forms.Textarea)
    time = forms.CharField(max_length=20, required=False, strip=True)

    def clean(self):
        cleaned_data = super().clean()
        delivery_type = cleaned_data.get('delivery_type')
        address = cleaned_data.get('address', '').strip()

        if delivery_type == 'delivery' and not address:
            self.add_error('address', 'Укажите адрес доставки.')

        return cleaned_data
