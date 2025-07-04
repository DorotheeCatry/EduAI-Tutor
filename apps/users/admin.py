from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import KodaUser

@admin.register(KodaUser)
class KodaUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_staff", "xp", "level_display")

    # On regroupe les champs dans des sections
    fieldsets = UserAdmin.fieldsets + (
        (_("Profil utilisateur"), {
            "fields": ("bio", "avatar", "language_preference"),
        }),
        (_("Progression"), {
            "fields": ("role", "xp"),
        }),
    )

    # On rend certains champs non modifiables
    readonly_fields = ("bio", "avatar", "language_preference")

    def level_display(self, obj):
        return obj.level
    level_display.short_description = _("Level")
