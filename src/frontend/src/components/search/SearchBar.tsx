import { useState } from 'react';
import { Button } from '../ui/button';

type SearchBarProps = {
  onSearch: (query: string) => void;
};

export function SearchBar({ onSearch }: SearchBarProps) {
  const [query, setQuery] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim());
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl mx-auto">
      <div className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="输入关键词进行搜索..."
          className="flex-1 bg-background border border-input rounded-md px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary/50"
        />
        <Button type="submit" variant="default">
          搜索
        </Button>
      </div>
    </form>
  );
} 