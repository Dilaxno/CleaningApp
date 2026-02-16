# Vulture whitelist for intentionally unused variables
# These are required by framework signatures and cannot be removed

# Pydantic validators require 'cls' parameter
_.cls  # unused variable (Pydantic @classmethod validators)

# SQLAlchemy event listeners require specific signatures
_.cursor  # unused variable (SQLAlchemy event listener)
_.parameters  # unused variable (SQLAlchemy event listener)
_.executemany  # unused variable (SQLAlchemy event listener)

# ARQ worker context parameter
_.ctx  # unused variable (ARQ worker context)

# Model imports are required for SQLAlchemy relationship resolution
_.models  # unused import (SQLAlchemy model registration)
_.models_google_calendar  # unused import (SQLAlchemy model registration)
_.models_invoice  # unused import (SQLAlchemy model registration)
_.models_quickbooks  # unused import (SQLAlchemy model registration)
_.models_square  # unused import (SQLAlchemy model registration)
