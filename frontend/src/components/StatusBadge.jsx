import React from 'react';

export default function StatusBadge({ status, multiMarked }) {
  if (status === 'ERROR' || status === 'failed') {
    return (
      <span
        className="badge badge-danger"
        style={{
          background: '#fef2f2',
          color: '#dc2626',
          border: '1px solid #fecaca',
          fontWeight: 700,
          padding: '0.25rem 0.6rem',
        }}
      >
        ERROR
      </span>
    );
  }
  if (multiMarked || status === 'MULTI_MARKED') {
    return <span className="badge badge-warning">Multi-marcada</span>;
  }
  if (status === 'SUCCESS' || status === 'completed') {
    return <span className="badge badge-success">Correcto</span>;
  }
  return <span className="badge badge-warning">{status || 'Pendiente'}</span>;
}
