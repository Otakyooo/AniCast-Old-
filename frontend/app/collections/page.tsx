import { redirect } from "next/navigation";

// Collections are a view inside the profile library (design freeze v0.2,
// acceptance #5), not a standalone global section.
export default function CollectionsPage() {
  redirect("/library?view=collections");
}
