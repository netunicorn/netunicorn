// Navbar.tsx
import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import './Navbar.css';
import Button from '@mui/material/Button';

interface NavbarProps {
  setIsAuthenticated: (value: boolean) => void;
}

const Navbar: React.FC<NavbarProps> = ({ setIsAuthenticated }) => {
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('netunicorn_access_token');
    setIsAuthenticated(false);
    navigate('/login');
  };

  if (location.pathname === '/login') {
    return null;
  }

  return (
    <nav className="custom-navbar">
      <div className="custom-navbar-brand">
        <Link to="/" className="custom-navbar-logo">netflex</Link>
      </div>

      <ul className="custom-navbar-list">
        <li className="custom-navbar-item">
          <Link to="/experiments">Experiments</Link>
        </li>
        <li className="custom-navbar-item">
          <Link to="/nodes">Nodes</Link>
        </li>
        <li className="custom-navbar-item">
          <Link to="/compilations">Compilations</Link>
        </li>
        <li className="custom-navbar-item">
          <Link id="create-tab" to="/run">Run</Link>
        </li>
      </ul>

      <ul className="custom-navbar-list">
        <li className="custom-navbar-item">
          <Button 
            variant="outlined" 
            color="secondary" 
            onClick={handleLogout}
            sx={{ 
              color: 'white',
              borderColor: 'white',
              '&:hover': {
                borderColor: 'white',
                backgroundColor: 'rgba(255, 255, 255, 0.08)' 
              }
            }}
          
          >
            Logout
          </Button>
        </li>
      </ul>
    </nav>
  );
};

export default Navbar;