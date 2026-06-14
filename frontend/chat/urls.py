from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path("",           views.chat_view,          name="chat"),
    path("login/",     views.login_view,          name="login"),
    path("logout/",    views.logout_view,         name="logout"),
    path("register/",  views.register_view,       name="register"),

    # Chat API proxies
    path("send/",      views.send_message,        name="send"),
    path("history/",   views.history,             name="history"),

    # Sessions (sidebar)
    path("api/sessions/",                      views.sessions,        name="sessions"),
    path("api/sessions/<str:session_id>/delete/", views.session_delete, name="session_delete"),

    # User profile
    path("profile/",   views.profile_view,        name="profile"),

    # Admin — Claims
    path("admin/claims/",                              views.admin_claims_view,    name="admin_claims"),
    path("admin/claims/<int:claim_id>/decision/",      views.admin_claim_decision, name="admin_claim_decision"),

    # Admin — Support Tickets
    path("admin/tickets/",                             views.admin_tickets_view,   name="admin_tickets"),
    path("admin/tickets/<int:ticket_id>/close/",       views.admin_close_ticket,   name="admin_close_ticket"),
]
