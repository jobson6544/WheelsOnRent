import stripe
from django.conf import settings
from django.urls import reverse

stripe.api_key = settings.STRIPE_SECRET_KEY

def create_checkout_session(request, amount, booking_id):
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': int(amount * 100),  # amount in cents
                        'product_data': {
                            'name': 'Vehicle Rental',
                        },
                    },
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=request.build_absolute_uri(reverse('payment_success')) + f'?session_id={{CHECKOUT_SESSION_ID}}&booking_id={booking_id}',
            cancel_url=request.build_absolute_uri(reverse('payment_cancelled')) + f'?booking_id={booking_id}',
            client_reference_id=booking_id,
        )
        return checkout_session, None
    except stripe.error.StripeError as e:
        return None, str(e)
