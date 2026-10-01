import mongoose from 'mongoose';

let isMongoConnected = false;

export const connectDB = async () => {
  const uri = process.env.MONGO_URI;

  if (!uri) {
    console.log('ℹ️  No MONGO_URI specified in .env. Running in Mock In-Memory Mode.');
    isMongoConnected = false;
    return false;
  }

  try {
    // Attempt connection with short serverSelectionTimeoutMS to avoid blocking startup if local mongo isn't up
    const conn = await mongoose.connect(uri, {
      serverSelectionTimeoutMS: 2500,
    });
    isMongoConnected = true;
    console.log(` MongoDB Connected: ${conn.connection.host}`);
    return true;
  } catch (error) {
    console.warn(`⚠️  MongoDB Connection failed: ${error.message}`);
    console.log('ℹ️  Falling back to Mock In-Memory Mode. Backend remains 100% operational!');
    isMongoConnected = false;
    return false;
  }
};

export const getDBStatus = () => {
  return {
    isConnected: isMongoConnected,
    state: isMongoConnected ? 'connected' : 'mock-fallback'
  };
};
