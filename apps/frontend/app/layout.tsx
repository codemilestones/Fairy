import type { ReactNode } from "react";

export const metadata = {
  title: "Fairy Demo",
  description: "Research Agent web demo"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body style={{ margin: 0, fontFamily: "ui-sans-serif, system-ui" }}>
        {children}
      </body>
    </html>
  );
}


