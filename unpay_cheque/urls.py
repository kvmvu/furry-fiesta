from django.urls import path, include
from rest_framework.routers import DefaultRouter
from unpay_cheque import views

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'unpaids', views.UnpaidViewSet)
router.register(r'users', views.UserViewSet)
router.register(r'charges', views.ChargeViewSet)

# The API URLs are now determined automatically by the router.
urlpatterns = [
    path('', include(router.urls)),
]