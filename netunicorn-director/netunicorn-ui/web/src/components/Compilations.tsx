import React, { useEffect, useState } from 'react';
import 'bootstrap/dist/css/bootstrap.min.css';
import SearchableTable from './SearchableTable.tsx';
import { Compilation, getActiveCompilations } from '../api/api-requests.ts';
import Alert from '@mui/material/Alert';

function Compilations() {
    const [compilations, setCompilations] = useState<Compilation[]>([]);
    const [error, setError] = useState('');

    const compilation_fields = ["username", "experiment_name", "experiment_id", "compilation_id", "architecture"] as unknown as (keyof Compilation)[];

    useEffect(() => {
        const getCompilations = async () => {
          try {
            const response = await getActiveCompilations();
            setCompilations(response); 
          } catch (err: any) {
            setError(err?.message || 'Failed to load compilations');
          }
        };
    
        getCompilations();
      }, []);
    
    const func = ({ data }: { data: Compilation[] }) => {
        return data.map((item) => (
          <tr key={item.experiment_id}>
            <td>{item.username}</td>
            <td>{item.experiment_name}</td>
            <td>{item.experiment_id}</td>
            <td>{item.compilation_id}</td>
            <td>{item.architecture}</td>
          </tr>
        ));
      };
    

    return (
        <div>
            {error && (
            <Alert severity="error">
                {error}
            </Alert>
            )}
            <SearchableTable
                title="Active Compilations"
                fields={compilation_fields}
                data={compilations}
                MapFunc={func}
            />
        </div>
    );
}

export default Compilations;