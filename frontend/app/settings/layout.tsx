import { SettingsMenu } from "@/components/settings/SettingsMenu";
import { SetupGate } from "@/components/setup/SetupGate";

/** Settings: its menu in the sidebar's place beside the settings page open, once setup is done. */
export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SetupGate>
      <SettingsMenu />
      <main className="flex min-w-0 flex-1 flex-col">{children}</main>
    </SetupGate>
  );
}
