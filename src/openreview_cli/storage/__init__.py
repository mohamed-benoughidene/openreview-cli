"""Storage layer — SQLite database with migration support."""

from openreview_cli.storage.clients import (
    add_client,
    client_has_reviews,
    delete_client,
    get_client,
    list_clients,
)
from openreview_cli.storage.comparisons import (
    list_comparison_history,
    record_comparison,
)
from openreview_cli.storage.costs import (
    check_daily_limit,
    check_session_limit,
    get_session_cost,
    log_cost,
)
from openreview_cli.storage.database import (
    get_connection,
    init_database,
    transaction,
)
from openreview_cli.storage.graphs import (
    load_graph,
    save_graph,
)
from openreview_cli.storage.playbooks import (
    delete_playbook,
    diff_playbook_versions,
    ensure_playbook_meta,
    export_playbook_version,
    get_current_version,
    get_latest_playbook_version,
    get_playbook_history,
    get_playbook_version,
    import_playbook_yaml,
    list_playbooks,
    list_playbooks_with_meta,
    set_current_version,
)
from openreview_cli.storage.recovery import (
    delete_recovery_state,
    load_recovery_state,
    save_recovery_state,
)
from openreview_cli.storage.reviews import (
    list_recent_reviews,
    list_reviews_for_client,
    load_review_report,
    save_review_report,
)
from openreview_cli.storage.search import (
    search_all,
)

__all__ = [
    "add_client",
    "check_daily_limit",
    "check_session_limit",
    "client_has_reviews",
    "delete_client",
    "delete_playbook",
    "delete_recovery_state",
    "diff_playbook_versions",
    "ensure_playbook_meta",
    "export_playbook_version",
    "get_client",
    "get_connection",
    "get_current_version",
    "get_latest_playbook_version",
    "get_playbook_history",
    "get_playbook_version",
    "get_session_cost",
    "import_playbook_yaml",
    "init_database",
    "list_clients",
    "list_comparison_history",
    "list_playbooks",
    "list_playbooks_with_meta",
    "list_recent_reviews",
    "list_reviews_for_client",
    "load_graph",
    "load_recovery_state",
    "load_review_report",
    "log_cost",
    "record_comparison",
    "save_graph",
    "save_recovery_state",
    "save_review_report",
    "search_all",
    "set_current_version",
    "transaction",
]
