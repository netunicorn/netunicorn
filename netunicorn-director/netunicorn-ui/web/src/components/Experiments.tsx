import React, { useState, useEffect } from 'react';
import 'bootstrap/dist/css/bootstrap.min.css';
import SearchableTable from './SearchableTable.tsx';
import { Experiment, getRunningExperiments, getLastExperiments } from '../api/api-requests.ts';
import Alert from '@mui/material/Alert';

function Experiments() {
  const [runningExperiments, setRunningExperiments] = useState<Experiment[]>([]);
  const [runningError, setRunningError] = useState('');

  const [lastExperiments, setLastExperiments] = useState<Experiment[]>([]);
  const [lastError, setLastError] = useState('');

  const experiment_fields: (keyof Experiment)[] = [
    'username',
    'experiment_name',
    'experiment_id',
    'status',
    'error',
    'creation_time',
    'start_time',
    'nodes',
  ];

  const func = ({ data }: { data: Experiment[] }) => {
    return data.map((item) => (
      <tr key={item.experiment_id}>
        <td>{item.username}</td>
        <td>{item.experiment_name}</td>
        <td>{item.experiment_id}</td>
        <td>{item.status}</td>
        <td>{item.error ?? '-'}</td>
        <td>{item.creation_time}</td>
        <td>{item.start_time ?? '-'}</td>
        <td>{item.nodes ?? '-'}</td>
      </tr>
    ));
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const running = await getRunningExperiments();
        setRunningExperiments(running);
      } catch (err: any) {
        setRunningError(err?.message || 'Failed to load running experiments');
      }

      try {
        const history: Experiment[] = await getLastExperiments();
        setLastExperiments(history);
      } catch (err: any) {
        setLastError(err?.message || 'Failed to load experiment history');
      }
    };

    fetchData();
  }, []);

  return (
    <div>
      {runningError && (
        <Alert severity="error">
          {runningError}
        </Alert>
      )}
      <SearchableTable
        title="Running Experiments"
        fields={experiment_fields}
        data={runningExperiments}
        MapFunc={func}
      />

      {lastError && (
        <Alert severity="error">
          {lastError}
        </Alert>
      )}
      <SearchableTable
        title="Experiments History"
        fields={experiment_fields}
        data={lastExperiments}
        MapFunc={func}
      />
    </div>
  );
}

export default Experiments;