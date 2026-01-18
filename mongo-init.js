// mongo-init.js
db = db.getSiblingDB("resumes_db");

print("Starting MongoDB initialization...");

// Create collections if they don't exist
if (!db.getCollectionNames().includes("resumes")) {
  db.createCollection("resumes");
  print(" Created 'resumes' collection");
} else {
  print("⚠️ 'resumes' collection already exists");
}

// Drop existing indexes and recreate (to ensure they're correct)
db.resumes.dropIndexes();

// Create indexes for better performance
db.resumes.createIndex({ source_url: 1 }, { unique: true });
print(" Created unique index on 'source_url'");

db.resumes.createIndex({ qdrant_status: 1 });
print(" Created index on 'qdrant_status'");

db.resumes.createIndex({ scraped_at: -1 }); // Descending for recent first
print(" Created index on 'scraped_at'");

db.resumes.createIndex({ category: 1 });
print(" Created index on 'category'");

db.resumes.createIndex({ processing_status: 1 });
print(" Created index on 'processing_status'");

// Insert test documents only if they don't exist
const testDoc = db.resumes.findOne({ _id: "test-resume-001" });
if (!testDoc) {
  db.resumes.insertOne({
    _id: "test-resume-001",
    source_url: "https://example.com/test-resume",
    category: "software_engineer",
    domain: "Software Engineering",
    job_role: "Test Engineer",
    qdrant_status: "pending",
    processing_status: "test_data",
    scraped_at: new Date(),
    experiences: [
      {
        job_role: "Test Developer",
        environment: "Python, Testing",
        responsibilities: ["Testing pipeline", "Writing test cases"],
      },
    ],
    skills: ["Python", "Testing", "Docker"],
  });
  print(" Inserted test document");
} else {
  print("⚠️ Test document already exists");
}

print("🎉 MongoDB initialization completed successfully!");
