import Card from '../components/ui/Card.jsx'
import PageHeader from '../components/layout/PageHeader.jsx'

export default function Placeholder({ title }) {
  return (
    <>
      <PageHeader title={title} />
      <Card className="gap-2">
        <h2 className="m-0 text-lg font-bold">This screen isn't built yet</h2>
        <p className="m-0 max-w-[60ch] text-sm leading-relaxed text-muted">
          The route and navigation work. The layout from the design file gets ported here in a later step.
        </p>
      </Card>
    </>
  )
}
