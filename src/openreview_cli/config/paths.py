from pathlib import Path


def get_config_dir() -> Path:
    from platformdirs import user_config_dir

    return Path(user_config_dir("openreview", ensure_exists=True))


def get_log_dir() -> Path:
    from platformdirs import user_log_dir

    return Path(user_log_dir("openreview", ensure_exists=True))


def get_data_dir() -> Path:
    from platformdirs import user_data_dir

    return Path(user_data_dir("openreview", ensure_exists=True))


def get_review_dir(review_id: str) -> Path:
    return get_data_dir() / "reviews" / review_id
