"""Audited ticket deletion for the support desk."""
from datetime import datetime, timezone
from sqlalchemy import text
from src.database.models import Ticket
from src.database.database import SessionLocal

NORMAL_STATUSES = {'Resolved', 'Closed'}
STUCK_STATUSES = {'Waiting for Human Review', 'Review in Progress'}

def ensure_delete_audit_table():
    with SessionLocal() as session:
        session.execute(text('''CREATE TABLE IF NOT EXISTS ticket_deletion_audit (
          id BIGSERIAL PRIMARY KEY, ticket_id VARCHAR(100) NOT NULL,
          previous_status VARCHAR(100), deletion_type VARCHAR(30) NOT NULL,
          deleted_by VARCHAR(255) NOT NULL, reason TEXT NOT NULL,
          deleted_at TIMESTAMPTZ NOT NULL)'''))
        session.commit()

def _delete(ticket_id, allowed_statuses, deletion_type, deleted_by, reason):
    if not ticket_id or not ticket_id.strip():
        raise ValueError('Ticket ID required')
    with SessionLocal() as session:
        ticket = session.query(Ticket).filter(Ticket.ticket_id == ticket_id.strip()).with_for_update().first()
        if ticket is None:
            return False
        if ticket.status not in allowed_statuses:
            raise ValueError(f'Deletion prohibited for status: {ticket.status}')
        session.execute(text('''INSERT INTO ticket_deletion_audit
          (ticket_id,previous_status,deletion_type,deleted_by,reason,deleted_at)
          VALUES (:ticket_id,:status,:kind,:actor,:reason,:deleted_at)'''),
          {'ticket_id':ticket_id.strip(),'status':ticket.status,'kind':deletion_type,
           'actor':deleted_by,'reason':reason,'deleted_at':datetime.now(timezone.utc)})
        session.delete(ticket)
        session.commit()
        return True

def delete_ticket(ticket_id):
    return _delete(ticket_id, NORMAL_STATUSES, 'NORMAL', 'local_admin', 'Completed ticket deletion')

def force_delete_ticket(ticket_id, reason, admin_identity, checkpoint_verified_missing):
    if not admin_identity or not admin_identity.strip():
        raise PermissionError('Authenticated administrator required')
    if not reason or len(reason.strip()) < 15:
        raise ValueError('Provide at least 15 characters of reason')
    if not checkpoint_verified_missing:
        raise ValueError('Missing checkpoint must be verified')
    return _delete(ticket_id, STUCK_STATUSES, 'FORCE', admin_identity, reason.strip())
