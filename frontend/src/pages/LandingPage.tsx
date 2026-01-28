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
        y: 24,
        opacity: 0,
        duration: 0.9,
        stagger: 0.12,
        ease: 'power3.out',
      });
      gsap.from('.metric', {
        y: 20,
        opacity: 0,
        duration: 0.8,
        stagger: 0.08,
        delay: 0.4,
        ease: 'power2.out',
      });
    }, heroRef);

    return () => ctx.revert();
  }, []);

  return (
    <div className="page landing">
      <div className="landing-top">
        <div className="brand">
          <img src="/logo.svg" alt="TerraCube IDEAS logo" />
          <span>TerraCube IDEAS</span>
        </div>
        <Link to="/login" className="button-secondary">
          Sign in
        </Link>
      </div>
      <section className="landing-hero" ref={heroRef}>
        <div>
          <span className="badge hero-animate">IVEA3H DGGS + IDEAS Model</span>
          <h1 className="hero-title hero-animate">TerraCube IDEAS Web GIS</h1>
          <p className="hero-tagline hero-animate">
            Visualize discrete global grid intelligence without server-side geometry. Store DGGS cell objects in Postgres,
            render IVEA3H shapes client-side, and orchestrate analytics through table-first operations.
          </p>
          <div className="hero-actions hero-animate">
            <Link to="/login" className="button-primary">Launch Dashboard</Link>
            <a href="#features" className="button-secondary">See Capabilities</a>
          </div>
        </div>
        <div className="hero-card hero-animate">
          <strong>IDEAS data model</strong>
          <p>Every cell-object stores a 5-tuple: dggid, tid, key, value, dataset. Flexible, scalable, and DGGS-native.</p>
          <div className="hero-metrics">
            <div className="metric">
              <strong>IVEA3H</strong>
              <span>Equal-area hexagonal DGGS</span>
            </div>
            <div className="metric">
              <strong>Deck.gl</strong>
              <span>GPU rendering for DGGS layers</span>
            </div>
            <div className="metric">
              <strong>MinIO + Redis</strong>
              <span>Staging and preprocessing pipeline</span>
            </div>
          </div>
        </div>
      </section>

      <section className="landing-band" id="features">
        {[
          {
            title: 'DGGS-native queries',
            text: 'Transform GIS operations into SQL filters, ranges, and aggregates without spatial indexes.',
          },
          {
            title: 'Client-side geometry',
            text: 'Use DGGAL WASM to generate zone vertices in the browser for fast, secure visualization.',
          },
          {
            title: 'Hybrid ingestion pipeline',
            text: 'Stage raster/vector uploads, preprocess to IDEAS cell objects, and reuse datasets instantly.',
          },
          {
            title: 'Layered analytics',
            text: 'Search datasets, load cell layers, and run analytic tooling from a single dashboard.',
          },
        ].map((item, index) => (
          <motion.div
            className="band-card"
            key={item.title}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: index * 0.1 }}
            viewport={{ once: true }}
          >
            <h3>{item.title}</h3>
            <p>{item.text}</p>
          </motion.div>
        ))}
      </section>

      <footer className="landing-footer">
        <p>Powered by <a href="https://github.com/ecere/dggal" target="_blank" rel="noopener noreferrer">DGGAL</a> &copy; 2025 TerraCube IDEAS</p>
      </footer>
    </div >
  );
};

export default LandingPage;
