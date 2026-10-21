import "./globals.css";

export const metadata = {
  title: "Login",
  description: "Simple login page",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
