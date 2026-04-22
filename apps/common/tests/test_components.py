from django.template.loader import render_to_string


class Page:
    def __init__(self, number, has_prev, has_next, start, end, count, pages):
        self.number = number
        self._prev = number - 1
        self._next = number + 1
        self._has_prev = has_prev
        self._has_next = has_next
        self.paginator = type(
            "P", (), {"count": count, "page_range": range(1, pages + 1), "num_pages": pages}
        )()
        self._start = start
        self._end = end

    def has_previous(self):
        return self._has_prev

    def has_next(self):
        return self._has_next

    def previous_page_number(self):
        return self._prev

    def next_page_number(self):
        return self._next

    def start_index(self):
        return self._start

    def end_index(self):
        return self._end


def test_button_primary_renders_yellow_classes():
    out = render_to_string(
        "components/buttons.html", {"variant": "primary", "label": "Save", "type": "submit"}
    )
    assert "bg-yellow" in out
    assert "text-black" in out
    assert "Save" in out
    assert 'type="submit"' in out
    assert 'data-testid="btn-primary"' in out


def test_button_danger_renders_red():
    out = render_to_string("components/buttons.html", {"variant": "danger", "label": "Delete"})
    assert "bg-red" in out
    assert "text-white" in out


def test_button_disabled_is_pointer_events_none():
    out = render_to_string(
        "components/buttons.html", {"variant": "primary", "label": "X", "disabled": True}
    )
    assert "opacity-50" in out
    assert "cursor-not-allowed" in out
    assert "disabled" in out


def test_password_field_has_alpine_eye_toggle():
    out = render_to_string(
        "components/form_fields.html",
        {"name": "password", "label": "Password", "type": "password"},
    )
    assert 'x-data="{ show: false }"' in out
    assert "show ? 'text' : 'password'" in out
    assert "Show password" in out


def test_field_with_error_has_red_border_and_alert_role():
    out = render_to_string(
        "components/form_fields.html",
        {"name": "email", "label": "Email", "type": "email", "error": "Required"},
    )
    assert "border-red" in out
    assert 'role="alert"' in out
    assert "Required" in out


def test_badge_green_renders_dot_and_tint():
    out = render_to_string(
        "components/badges.html", {"variant": "green", "label": "Active", "dot": True}
    )
    assert "bg-green-tint" in out
    assert "bg-green" in out  # dot
    assert "Active" in out
    assert 'data-testid="badge-green"' in out


def test_empty_state_renders_icon_title_desc_cta():
    out = render_to_string(
        "components/empty_state.html",
        {
            "icon": "building-2",
            "title": "No organisations yet",
            "description": "Create your first organisation to start onboarding stores.",
            "cta_label": "+ Create your first organisation",
            "cta_href": "/organisations/new/",
        },
    )
    assert "bg-yellow-tint" in out
    assert "No organisations yet" in out
    assert "+ Create your first organisation" in out
    assert 'href="/organisations/new/"' in out


def test_skeleton_has_aria_busy_and_pulse_class():
    out = render_to_string("components/skeletons.html", {"width": "140px", "height": "14px"})
    assert 'aria-busy="true"' in out
    assert "animate-sk-pulse" in out
    assert "bg-line" in out


def test_toasts_container_listens_for_custom_event():
    out = render_to_string("components/toasts.html", {})
    assert '@app:toast.window="add($event.detail)"' in out
    assert 'data-testid="toast-stack"' in out
    # Role binding is dynamic (:role)
    assert ":role=\"toast.kind === 'error' ? 'alert' : 'status'\"" in out


def test_pagination_active_is_black_yellow():
    page = Page(number=1, has_prev=False, has_next=True, start=1, end=8, count=47, pages=5)
    out = render_to_string("components/pagination.html", {"page_obj": page})
    assert "bg-black text-yellow" in out
    assert 'aria-current="page"' in out
    # Prev disabled styling
    assert 'aria-disabled="true"' in out
    assert "Showing" in out


def test_filter_bar_search_input_present():
    out = render_to_string(
        "components/filter_bar.html",
        {
            "status_options": [("", "All statuses"), ("ACTIVE", "Active")],
            "type_options": [("", "All types")],
            "search_placeholder": "Search organisations",
            "request": type("R", (), {"GET": {}})(),
        },
    )
    assert 'name="search"' in out
    assert "All statuses" in out
    assert "rounded-menu" in out
