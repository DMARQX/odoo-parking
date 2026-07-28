import io
import logging

from odoo import models
from weasyprint import HTML

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _run_wkhtmltopdf(self, bodies, report_ref=False, header=None, footer=None, **kwargs):
        """Override to use WeasyPrint for proper Arabic text shaping."""
        try:
            pdf_parts = []
            for body in bodies:
                pdf_bytes = HTML(string=body).write_pdf()
                pdf_parts.append(io.BytesIO(pdf_bytes))

            if len(pdf_parts) == 1:
                return pdf_parts[0].getvalue()
            else:
                return self._merge_pdfs(pdf_parts)
        except Exception as e:
            _logger.error("WeasyPrint failed: %s", e, exc_info=True)
            return super()._run_wkhtmltopdf(
                bodies, report_ref=report_ref, header=header, footer=footer, **kwargs
            )
