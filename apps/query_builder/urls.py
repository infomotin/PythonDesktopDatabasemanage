from django.urls import path
from apps.query_builder import views

app_name = "query_builder"
urlpatterns = [
    path("", views.QueryBuilderView.as_view(), name="index"),
    path("new/", views.CreateQueryView.as_view(), name="create"),
    path("history/", views.QueryHistoryView.as_view(), name="history"),
    path("saved/", views.SavedQueriesView.as_view(), name="saved"),
    path("execute/", views.ExecuteQueryView.as_view(), name="execute"),
    path("<int:query_id>/", views.QueryDetailView.as_view(), name="detail"),
    path("<int:query_id>/edit/", views.EditQueryView.as_view(), name="edit"),
    path("<int:query_id>/delete/", views.DeleteQueryView.as_view(), name="delete"),
    path("api/schema/", views.SchemaAPI.as_view(), name="schema_api"),
    path("api/execute/", views.ExecuteQueryAPI.as_view(), name="execute_api"),
    path("api/column-names/", views.ColumnNamesAPI.as_view(), name="column_names_api"),
]
