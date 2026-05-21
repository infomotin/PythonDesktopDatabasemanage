from django.urls import path
from apps.tables import views

app_name = "tables"
urlpatterns = [
    path("", views.TableView.as_view(), name="tables"),
    path("<uuid:table_id>/", views.TableDetailView.as_view(), name="detail"),
    path("<uuid:table_id>/row/edit/", views.TableRowEditView.as_view(), name="row_edit"),
    path("<uuid:table_id>/row/delete/", views.TableRowDeleteView.as_view(), name="row_delete"),
    path("<uuid:table_id>/download/", views.DownloadTableView.as_view(), name="download"),
    path("api/schema/", views.TableSchemaAPI.as_view(), name="schema_api"),
    path("api/index-suggestions/", views.IndexSuggestionAPI.as_view(), name="index_suggestions"),
]
