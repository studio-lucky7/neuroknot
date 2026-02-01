import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
// GNB 대신 NavigationWrapper를 사용합니다.
import NavigationWrapper from "@/components/NavigationWrapper"; 

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "NeuroKnot - 인지 독해 엔진",
  description: "당신의 독해 엔진을 가동하세요",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        {/* 직접 넣었던 GNB와 ml-64 div를 제거하고 Wrapper로 감쌉니다. */}
        <NavigationWrapper>
          {children}
        </NavigationWrapper>
      </body>
    </html>
  );
}