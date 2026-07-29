export default function StatCard({
  title,
  value,
  description,
  icon: Icon,
  tone = 'blue',
}) {
  return (
    <article className={`stat-card tone-${tone}`}>
      <div className="stat-icon">
        <Icon size={23} />
      </div>

      <div className="stat-card-content">
        <span>{title}</span>
        <strong>{value}</strong>
        <small>{description}</small>
      </div>
    </article>
  )
}
