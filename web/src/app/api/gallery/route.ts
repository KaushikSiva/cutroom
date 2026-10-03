import { admin } from "@/lib/server";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const { data } = await admin()
      .from("projects")
      .select("id,title,logline,brief,topic,aspect_ratio,length_s,status,stage,progress,video_url,video_4k_url,poster_url,created_at")
      .eq("is_public", true)
      .order("created_at", { ascending: false })
      .limit(24);
    return Response.json({ projects: data || [] });
  } catch (e) {
    return Response.json({ projects: [], error: (e as Error).message });
  }
}
