import Studio from "@/components/Studio";

export default async function Page({ params }: PageProps<"/p/[id]">) {
  const { id } = await params;
  return <Studio id={id} />;
}
