from django.contrib import admin
from .models import Exercise, ExerciseSubmission, UserExerciseProgress

@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ('title', 'difficulty', 'topic', 'created_by', 'attempts_count', 'success_rate', 'is_active')
    list_filter = ('difficulty', 'topic', 'is_active', 'created_at')
    search_fields = ('title', 'description', 'topic')
    readonly_fields = ('attempts_count', 'success_count', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('title', 'description', 'difficulty', 'topic', 'is_active')
        }),
        ('Code', {
            'fields': ('starter_code', 'solution', 'tests')
        }),
        ('Statistiques', {
            'fields': ('attempts_count', 'success_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(ExerciseSubmission)
class ExerciseSubmissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'exercise', 'status', 'execution_time', 'submitted_at')
    list_filter = ('status', 'submitted_at', 'exercise__difficulty')
    search_fields = ('user__username', 'exercise__title')
    readonly_fields = ('submitted_at', 'execution_time', 'test_results')
    
    def has_change_permission(self, request, obj=None):
        return False  # Lecture seule

@admin.register(UserExerciseProgress)
class UserExerciseProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'exercise', 'is_completed', 'attempts_count', 'completed_at')
    list_filter = ('is_completed', 'exercise__difficulty', 'completed_at')
    search_fields = ('user__username', 'exercise__title')
    readonly_fields = ('first_attempt_at', 'completed_at')