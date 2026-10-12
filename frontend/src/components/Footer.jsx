import { Link } from 'react-router-dom';

export default function Footer() {
  return (
    <footer className="border-t border-stone-200 bg-white">
      <div className="mx-auto flex max-w-[1120px] flex-wrap items-center justify-between gap-4 px-5 py-6">
        <span className="display text-[17px]">campus nest</span>
        <p className="font-mono text-[11.5px] text-stone-400">
          Summer storage near campus · pilot 2026
        </p>
        <div className="flex gap-5 text-[13px] text-stone-500">
          <Link to="/search" className="hover:text-stone-900">Browse</Link>
          <Link to="/list" className="hover:text-stone-900">List a space</Link>
          <Link to="/messages" className="hover:text-stone-900">Messages</Link>
        </div>
      </div>
    </footer>
  );
}
