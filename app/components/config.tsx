

export default function Config({
  title = "About",
  description = <></>,
}: {
  title?: string;
  description?: React.ReactNode;
}) {
  return (
    <fieldset className="grid gap-6 rounded-lg border p-4">
      <legend className="-ml-1 px-1 text-sm font-medium">{title}</legend>
      {description}
    </fieldset>
  );
}