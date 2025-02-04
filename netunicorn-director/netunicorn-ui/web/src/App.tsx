import React from 'react';
import './App.css';
import Navbar from './components/Navbar.tsx';
import { Route, Routes, BrowserRouter, Navigate} from 'react-router-dom';
import Experiments from './components/Experiments.tsx'
import Nodes from './components/Nodes.tsx'
import Compilations from './components/Compilations.tsx'
import Login from './components/Login.tsx';
import ProtectedRoute from './components/ProtectedRoute.tsx';
import Run from './components/Run.tsx'
import { useState } from 'react';



function Router() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  return (
    <div>
      <Navbar setIsAuthenticated={setIsAuthenticated}/>
      <Routes>
          <Route element={<ProtectedRoute isAuthenticated={isAuthenticated} />}>       
            <Route path="/experiments" element={ <Experiments/> } />
            <Route path="/nodes" element={ <Nodes/> } />
            <Route path="/compilations" element={ <Compilations/> } />
            <Route path="/run" element={ <Run/> } />
          </Route>
          <Route path="/login" element={<Login setIsAuthenticated={setIsAuthenticated} />} />
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </div>
  );
}

function App() {

  return (
    <BrowserRouter>
      <Router/>
    </BrowserRouter>
  );



  
}

export default App;
