

interface AgentAvatarProps {
  agentId: string
  role?: string
  size?: "sm" | "md" | "lg"
  className?: string
}

export function AgentAvatar({
  agentId,
  role,
  size = "md",
  className,
}: AgentAvatarProps) {
  const sizeClasses = {
    sm: "w-6 h-6",
    md: "w-8 h-8",
    lg: "w-10 h-10",
  }

  const roleChip = role ? (
    <span
      className={`inline-flex items-center rounded-full bg-${role === "owner" ? "rose" : role === "coordinator" ? "violet" : "teal"} bg-opacity-80 text-[0.65em] ml-1`}
    >
      {role.charAt(0)}
    </span>
  ) : null

  return (
    <div
      className={`
        ${sizeClasses[size]}
        rounded-md bg-surface border border-border
        ${className || ""}
      `}
    >
      {roleChip}
      <span className="self-center text-sm text-muted truncate">{agentId}</span>
    </div>
  )
}
