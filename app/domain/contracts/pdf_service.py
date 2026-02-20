"""Contract PDF generation service"""

import logging
from typing import Optional

from ...models import BusinessConfig

logger = logging.getLogger(__name__)


class ContractPDFService:
    """Service for contract PDF generation and management"""

    @staticmethod
    def calculate_estimated_hours(config: BusinessConfig, property_size: int) -> float:
        """Calculate estimated hours using three-category system or fallback to legacy"""

        # Try new three-category system first
        if config.time_small_job or config.time_medium_job or config.time_large_job:
            if property_size < 1500 and config.time_small_job:
                return config.time_small_job
            elif 1500 <= property_size <= 2500 and config.time_medium_job:
                return config.time_medium_job
            elif property_size > 2500 and config.time_large_job:
                return config.time_large_job
            else:
                # Fallback if specific category not configured
                if property_size < 1500:
                    return (
                        config.time_small_job
                        or config.time_medium_job
                        or config.time_large_job
                        or 1.5
                    )
                elif property_size > 2500:
                    return (
                        config.time_large_job
                        or config.time_medium_job
                        or config.time_small_job
                        or 4.0
                    )
                else:
                    return (
                        config.time_medium_job
                        or config.time_large_job
                        or config.time_small_job
                        or 2.5
                    )

        # Fallback to legacy system
        elif config.cleaning_time_per_sqft and property_size:
            return (property_size / 1000) * (config.cleaning_time_per_sqft / 60)

        # Final fallback to realistic estimates
        else:
            if property_size <= 800:
                return 1.5
            elif property_size <= 1500:
                return 2.5
            elif property_size <= 2500:
                return 3.5
            else:
                return 4.0

    @staticmethod
    def get_selected_package_details(config: BusinessConfig, form_data: dict) -> Optional[dict]:
        """Get details of the selected package for quote display"""
        selected_package_id = form_data.get("selectedPackage")
        if not selected_package_id or not config.custom_packages:
            return None

        for package in config.custom_packages:
            if package.get("id") == selected_package_id:
                return {
                    "id": package.get("id"),
                    "name": package.get("name", "Custom Package"),
                    "description": package.get("description", ""),
                    "included": package.get("included", []),
                    "duration": package.get("duration", 0),
                    "priceType": package.get("priceType", "flat"),
                    "price": package.get("price"),
                    "priceMin": package.get("priceMin"),
                    "priceMax": package.get("priceMax"),
                }

        return None

    @staticmethod
    def get_pdf_url(
        pdf_key: Optional[str], contract_public_id: Optional[str] = None
    ) -> Optional[str]:
        """Generate backend URL for PDF if key exists (avoids CORS issues)"""
        if not pdf_key or not contract_public_id:
            return None
        try:
            from ...config import FRONTEND_URL

            # Determine the backend base URL based on the frontend URL
            if "localhost" in FRONTEND_URL:
                backend_base = FRONTEND_URL.replace("localhost:5173", "localhost:8000").replace(
                    "localhost:5174", "localhost:8000"
                )
            else:
                backend_base = "https://api.cleanenroll.com"

            return f"{backend_base}/contracts/pdf/public/{contract_public_id}"
        except Exception:
            return None


# Note: The full calculate_quote function and PDF generation logic
# from contracts_pdf.py is kept in the original file for now.
# This will be fully extracted in a future refactoring phase.
# For now, we import and re-use the existing functions.
