import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../api/api-requests.ts';

import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

interface LoginProps {
    setIsAuthenticated: (value: boolean) => void;
}

const Login: React.FC<LoginProps> = ({ setIsAuthenticated }) => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const navigate = useNavigate();

    useEffect(() => {
        const token = localStorage.getItem('netunicorn_access_token');
        if (token) {
            setIsAuthenticated(true);
            navigate('/experiments');
        }
    }, [setIsAuthenticated, navigate]);

    const handleLogin = async () => {
        try {
          await login(username, password);
          const token = localStorage.getItem('netunicorn_access_token');
          if (token) {
            setIsAuthenticated(true);
            setError('');
            navigate('/experiments');
          } else {
            setError('Failed to authenticate.');
          }
        } catch (err: any) {
          setError(err.message || 'Failed to authenticate.');
        }
    };
      

    return (
        <Box
            sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '100vh',
                backgroundColor: '#f5f5f5',
                padding: 2,
            }}
        >
            <Box
                sx={{
                    width: 400,
                    padding: 4,
                    backgroundColor: 'white',
                    borderRadius: 2,
                    boxShadow: 3,
                }}
            >
                <Typography
                    sx={{ pb: 2 }}
                    variant="h5"
                    component="h1"
                    align="center"
                    gutterBottom
                    fontWeight="bold"
                >
                    NetFlex
                </Typography>
                <Box
                    component="form"
                    noValidate
                    autoComplete="off"
                    sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 2,
                    }}
                >
                    <TextField
                        label="Username"
                        variant="outlined"
                        size="small"
                        fullWidth
                        onChange={(e) => setUsername(e.target.value)}
                    />
                    <TextField
                        label="Password"
                        type="password"
                        variant="outlined"
                        size="small"
                        fullWidth
                        onChange={(e) => setPassword(e.target.value)}
                    />
                    <Button
                        variant="contained"
                        color="primary"
                        size="large"
                        disableElevation
                        onClick={handleLogin}
                        disabled={!username || !password}
                        fullWidth
                    >
                        Login
                    </Button>
                </Box>
                {error && (
                    <Alert severity="error" sx={{ marginTop: 2 }}>
                        {error}
                    </Alert>
                )}
            </Box>
        </Box>
    );
};

export default Login;