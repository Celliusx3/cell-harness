import { redirect } from "next/navigation";

/** Settings opens on Credentials. */
export default function SettingsPage() {
  redirect("/settings/credentials");
}
