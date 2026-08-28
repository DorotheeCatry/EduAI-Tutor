from django.urls import path
from .views import (
    CustomLoginView,
    CustomLogoutView,
    ProfileView,
    RegisterView,
    SuppressionCompteView,
)

app_name = 'users'

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('profile/', ProfileView.as_view(), name='profile'),
    # Droit à l'effacement — article 17 du RGPD.
    path('profile/supprimer/', SuppressionCompteView.as_view(),
         name='supprimer_compte'),
]
