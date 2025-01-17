import React, { useState, useEffect } from 'react';
import 'bootstrap/dist/css/bootstrap.min.css';
import SearchableTable from './SearchableTable.tsx';
import { LockedNode, getLockedNodes } from '../api/api-requests.ts';
import Alert from '@mui/material/Alert';

function Nodes() {
  const [lockedNodes, setLockedNodes] = useState<LockedNode[]>([]);
  const [error, setError] = useState('');

  const node_fields = ['username', 'node_name', 'connector'] as unknown as (keyof LockedNode)[];

  const func = ({ data }: { data: LockedNode[] }) => {
    return data.map((item, idx) => (
      <tr key={idx}>
        <td>{item.username}</td>
        <td>{item.node_name}</td>
        <td>{item.connector}</td>
      </tr>
    ));
  };

  useEffect(() => {
    const fetchNodes = async () => {
      try {
        const nodesData = await getLockedNodes();
        setLockedNodes(nodesData);
      } catch (err: any) {
        setError(err?.message || 'Failed to load locked nodes');
      }
    };

    fetchNodes();
  }, []);

  return (
    <div>
      {error && (
            <Alert severity="error">
                {error}
             </Alert>
        )}
      <SearchableTable
        title="Locked Nodes"
        fields={node_fields}
        data={lockedNodes}
        MapFunc={func}
      />
    </div>
  );
}

export default Nodes;