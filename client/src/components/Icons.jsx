const base = {
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": "true",
};

export function DashboardIcon() {
  return (
    <svg {...base}>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </svg>
  );
}

export function DocumentsIcon() {
  return (
    <svg {...base}>
      <path d="M7 3h7l4 4v14H7z" />
      <path d="M14 3v5h5" />
      <path d="M10 12h5M10 16h5" />
    </svg>
  );
}

export function PricesIcon() {
  return (
    <svg {...base}>
      <path d="M4 19V5M4 19h16" />
      <path d="M8 15l3-4 3 2 4-6" />
      <circle cx="8" cy="15" r="1" />
      <circle cx="11" cy="11" r="1" />
      <circle cx="14" cy="13" r="1" />
      <circle cx="18" cy="7" r="1" />
    </svg>
  );
}

export function ExceptionsIcon() {
  return (
    <svg {...base}>
      <path d="M12 3l9 17H3z" />
      <path d="M12 9v5M12 17h.01" />
    </svg>
  );
}

export function LogoutIcon() {
  return (
    <svg {...base}>
      <path d="M10 5H5v14h5" />
      <path d="M14 8l4 4-4 4M18 12H9" />
    </svg>
  );
}

export function UploadIcon() {
  return (
    <svg {...base}>
      <path d="M12 16V4M8 8l4-4 4 4" />
      <path d="M4 16v3h16v-3" />
    </svg>
  );
}

export function CheckIcon() {
  return (
    <svg {...base}>
      <path d="M5 12l4 4L19 6" />
    </svg>
  );
}

export function CloseIcon() {
  return (
    <svg {...base}>
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}

export function SearchIcon() {
  return (
    <svg {...base}>
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-4-4" />
    </svg>
  );
}

export function BillingIcon() {
  return (
    <svg {...base}>
      <rect x="3" y="5" width="18" height="14" rx="2.5" />
      <path d="M3 10h18M7 15h4" />
    </svg>
  );
}

export function TeamIcon() {
  return (
    <svg {...base}>
      <circle cx="9" cy="8" r="3" />
      <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" />
      <path d="M16 5.5a3 3 0 0 1 0 5.8M18 14.5c2.3.7 4 2.8 4 5.5" />
    </svg>
  );
}

export function ProfileIcon() {
  return (
    <svg {...base}>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20c0-3.9 3.1-7 7-7s7 3.1 7 7" />
    </svg>
  );
}

export function AdminIcon() {
  return (
    <svg {...base}>
      <path d="M12 3l8 4v5c0 5-3.4 8.3-8 9-4.6-.7-8-4-8-9V7z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  );
}

export function DownloadIcon() {
  return (
    <svg {...base}>
      <path d="M12 4v11M8 11l4 4 4-4" />
      <path d="M4 20h16" />
    </svg>
  );
}

export function SparkIcon() {
  return (
    <svg {...base}>
      <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />
      <path d="M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z" />
    </svg>
  );
}

export function CopyIcon() {
  return (
    <svg {...base}>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15H4V4h11v1" />
    </svg>
  );
}

export function ArrowIcon() {
  return (
    <svg {...base}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

export function ArrowRightIcon() {
  return <ArrowIcon />;
}

export function XIcon() {
  return <CloseIcon />;
}

export function BellIcon() {
  return (
    <svg {...base}>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.7 21a2 2 0 0 1-3.4 0" />
    </svg>
  );
}

export function SuppliersIcon() {
  return (
    <svg {...base}>
      <path d="M3 21V7l7-4 7 4v14" />
      <path d="M3 21h18M9 21v-4h4v4" />
      <path d="M7 10h2M7 14h2M13 10h2M13 14h2" />
    </svg>
  );
}

export function TrashIcon() {
  return (
    <svg {...base}>
      <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}

export function ArrowLeftIcon() {
  return (
    <svg {...base}>
      <path d="M19 12H5M12 5l-7 7 7 7" />
    </svg>
  );
}

export function MailIcon() {
  return (
    <svg {...base}>
      <path d="M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" />
      <polyline points="22,6 12,13 2,6" />
    </svg>
  );
}

export function LockIcon() {
  return (
    <svg {...base}>
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

export function AlertTriangleIcon() {
  return (
    <svg {...base}>
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <path d="M12 9v4M12 17h.01" />
    </svg>
  );
}

export function SettingsIcon() {
  return (
    <svg {...base}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

export function UsersIcon() {
  return (
    <svg {...base}>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}

export function PlusIcon() {
  return (
    <svg {...base}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function EditIcon() {
  return (
    <svg {...base}>
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

export function ShieldIcon() {
  return (
    <svg {...base}>
      <path d="M12 3l8 4v5c0 5-3.4 8.3-8 9-4.6-.7-8-4-8-9V7z" />
      <path d="M12 8v5M12 16h.01" />
    </svg>
  );
}

export function InfoIcon() {
  return (
    <svg {...base}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </svg>
  );
}

export function DollarIcon() {
  return (
    <svg {...base}>
      <path d="M12 1a9 9 0 0 1 9 9c0 2-1 3-2 4s-2 2-4 2-4-2-4-4 0-4 2-4s2-2 4-2" />
      <path d="M12 12h3" />
    </svg>
  );
}

export function RocketIcon() {
  return (
    <svg {...base}>
      <path d="M12 5l-4 4-4-4-2 2 8 8 8-8-2-2z" />
      <path d="M16 4l-4 4-4-4-2 2 8 8 8-8-2-2z" opacity="0.3" />
    </svg>
  );
}

export function CrownIcon() {
  return (
    <svg {...base}>
      <path d="M12 2l-4 4v4l-4-4-2 2 8 8 8-8-2-2z" />
      <path d="M12 10l-4 4-4-4-2 2 8 8 8-8-2-2z" opacity="0.3" />
    </svg>
  );
}

export function ClockIcon() {
  return (
    <svg {...base}>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

export function HelpIcon() {
  return (
    <svg {...base}>
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <path d="M12 17h.01" />
    </svg>
  );
}

export function HistoryIcon() {
  return (
    <svg {...base}>
      <circle cx="12" cy="12" r="10" />
      <path d="M8 16l4 4 8-8" />
      <path d="M12 16h.01" />
    </svg>
  );
}
