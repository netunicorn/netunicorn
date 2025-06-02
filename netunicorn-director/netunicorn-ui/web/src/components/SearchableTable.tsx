// SearchableTable.tsx
import React, { useState } from 'react';
import { Table, Form } from 'react-bootstrap';

interface SearchableTableProps<T> {
  title: string;
  fields: (keyof T)[];          
  data: T[];
  MapFunc: (args: { data: T[] }) => React.ReactNode;
}

const formatHeader = (field: string): string => {
  return field
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

function SearchableTable<T>({
  title,
  fields,
  data,
  MapFunc,
}: SearchableTableProps<T>) {
  const [searchInput, setSearchInput] = useState('');

  const filteredData = data.filter((row) => {
    const rowRecord = row as Record<string, any>;

    return fields.some((field) => {
      const value = rowRecord[field as string];
      if (!value) return false;
      return value.toString().toLowerCase().includes(searchInput.toLowerCase());
    });
  });

  const handleSearch = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchInput(event.target.value);
  };

  return (
    <div style={{ padding: '20px' }}>
      <h1>{title}</h1>
      <Form.Group className="mb-3" style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Form.Control
          style={{ width: '20%' }}
          type="text"
          placeholder="Search..."
          value={searchInput}
          onChange={handleSearch}
        />
      </Form.Group>

      <div style={{ overflowX: 'auto' }}>
        <Table striped bordered hover>
          <thead>
            <tr>
              {fields.map((field, index) => (
                <th key={index}>{formatHeader(String(field))}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <MapFunc data={filteredData} />
          </tbody>
        </Table>
      </div>
    </div>
  );
}

export default SearchableTable;