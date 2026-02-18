import { BrainProvider } from '@/contexts/BrainContext';

export default function BrainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <BrainProvider>{children}</BrainProvider>;
}
