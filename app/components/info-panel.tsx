interface Feature {
  title: string;
  description: string;
  query?: string;
  response?: string;
}

interface InfoPanelProps {
  features: Feature[];
}

export default function InfoPanel({ features }: InfoPanelProps) {
  return (
    <div className="hidden w-[350px] flex-shrink-0 flex-col gap-4 overflow-y-auto border-r bg-background p-4 md:flex">
      {features.map((feature, index) => (
        <FeatureCard key={index} feature={feature} />
      ))}
    </div>
  );
}

function FeatureCard({ feature }: { feature: Feature }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="mb-2 font-semibold">{feature.title}</h3>
      <p className="whitespace-pre-line text-sm text-muted-foreground">
        {feature.description}
      </p>
      {feature.query && (
        <div className="mt-4 rounded-md bg-muted/50 p-3">
          <p className="text-xs font-medium text-muted-foreground">Example:</p>
          <p className="mt-1 text-sm font-medium">{feature.query}</p>
          {feature.response && (
            <p className="mt-2 text-sm text-muted-foreground">
              {feature.response}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
