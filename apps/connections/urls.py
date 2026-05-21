from django.urls import path
from connections import views
app_name = "connections"
urlpatterns = [
    path("", views.ConnectionListView.as_view(), name="list"),
    path("create/", views.ConnectionCreateView.as_view(), name="create"),
    path("details/", views.ConnectionDetailView.as_view(), name="detail"),
    path("delete/", views.ConnectionDeleteView.as_view(), name="delete"),
    path("clone/", views.CloneDatabaseConnectionView.as_view(), name="clone"),
    path("execute/", views.ExecuteQueryView.as_view(), name="execute"),
    path("executing/", views.ExecutingAjaxView.as_view(), name="executing"),
]

