import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import gsap from 'gsap';

const LandingPage = () => {
  const heroRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!heroRef.current) return;
    const ctx = gsap.context(() => {
      gsap.from('.hero-animate', {
        y: 30,
        opacity: 0,
        duration: 1,
        stagger: 0.14,
        ease: 'power3.out',
      });
      gsap.from('.metric', {
        y: 18,
        opacity: 0,
        duration: 0.8,
        stagger: 0.08,
        delay: 0.5,
        ease: 'power2.out',
      });
      gsap.from('.hero-card', {
        x: 40,
        opacity: 0,
        duration: 1.1,
        delay: 0.3,
        ease: 'power3.out',
      });
    }, heroRef);

    return () => ctx.revert();
  }, []);

  return (
    <div className="page landing">
      <div className="landing-top">
        <div className="brand">
          <img src="/logo.svg" alt="TerraCube IDEAS" />
          <span>TerraCube IDEAS</span>
        </div>
        <Link to="/login" className="button-secondary">
          Sign in
        </Link>
      </div>

      <section className="landing-hero" ref={heroRef}>
        <div>
          <span className="badge hero-animate">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 0L10.39 3V9L6 12L1.61 9V3L6 0Z" fill="currentColor" opacity="0.5"/></svg>
            IVEA3H DGGS + IDEAS Model
          </span>
          <h1 className="hero-title hero-animate">
            Discrete Global Grid<br /><em>Intelligence</em>
          </h1>
          <p className="hero-tagline hero-animate">
            Visualize and analyze geospatial data on hexagonal DGGS grids.
            No server-side geometry. Store cell objects in Postgres, render
            shapes client-side, orchestrate analytics through table-first operations.
          </p>
          <div className="hero-actions hero-animate">
            <Link to="/login" className="button-primary">
              <span style={{ position: 'relative', zIndex: 1 }}>Launch Dashboard</span>
            </Link>
            <a href="#features" className="button-secondary">Explore Capabilities</a>
          </div>
        </div>

        <div className="hero-card">
          <strong>IDEAS Data Model</strong>
          <p>
            Every cell-object stores a 5-tuple: dggid, tid, key, value, dataset.
            Flexible, scalable, and DGGS-native.
          </p>
          <div className="hero-metrics">
            <div className="metric">
              <strong>IVEA3H</strong>
              <span>Equal-area hexagonal grid</span>
            </div>
            <div className="metric">
              <strong>Deck.gl</strong>
              <span>GPU-accelerated rendering</span>
            </div>
            <div className="metric">
              <strong>14+ Algorithms</strong>
              <span>Spatial analysis engine</span>
            </div>
          </div>
        </div>
      </section>

      <section className="landing-band" id="features">
        {[
          {
            title: 'DGGS-native queries',
            text: 'Transform GIS operations into SQL filters, ranges, and aggregates. No PostGIS, no spatial indexes required.',
          },
          {
            title: 'Client-side geometry',
            text: 'DGGAL WASM generates zone vertices in the browser for fast, secure visualization with zero server load.',
          },
          {
            title: 'Hybrid ingestion',
            text: 'Stage raster, vector, and CSV uploads. Preprocess to IDEAS cell objects via Celery workers.',
          },
          {
            title: 'Spatial analysis',
            text: "Moran's I, LISA, DBSCAN, viewshed, shortest path, kernel density, and more from a unified API.",
          },
        ].map((item, index) => (
          <motion.div
            className="band-card"
            key={item.title}
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: index * 0.1 }}
            viewport={{ once: true }}
          >
            <h3>{item.title}</h3>
            <p>{item.text}</p>
          </motion.div>
        ))}
      </section>

      <footer className="landing-footer">
        <p>
          Powered by{' '}
          <a href="https://github.com/ecere/dggal" target="_blank" rel="noopener noreferrer">DGGAL</a>
          {' '}&middot; &copy; 2025 TerraCube IDEAS
        </p>
      </footer>
    </div>
  );
};

export default LandingPage;
