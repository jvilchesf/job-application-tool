// MongoDB initialization script for job-application database
// Run with: mongosh < init_mongodb.js

// Switch to job_application database
use("job_application");

// Create jobs collection with schema validation
db.createCollection("jobs", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["linkedin_id", "title", "company", "status"],
      properties: {
        linkedin_id: {
          bsonType: "string",
          description: "LinkedIn job ID - required"
        },
        url: {
          bsonType: "string",
          description: "Job URL"
        },
        title: {
          bsonType: "string",
          description: "Job title - required"
        },
        company: {
          bsonType: "string",
          description: "Company name - required"
        },
        location: {
          bsonType: "string",
          description: "Job location"
        },
        description: {
          bsonType: "string",
          description: "Job description"
        },
        description_html: {
          bsonType: "string",
          description: "HTML job description"
        },
        description_translated: {
          bsonType: "string",
          description: "Translated job description"
        },
        salary: {
          bsonType: "string",
          description: "Salary information"
        },
        employment_type: {
          bsonType: "string",
          description: "Full-time, Part-time, Contract, etc."
        },
        experience_level: {
          bsonType: "string",
          description: "Entry, Mid, Senior, etc."
        },
        posted_date: {
          bsonType: "date",
          description: "When job was posted"
        },
        apply_url: {
          bsonType: "string",
          description: "Direct application URL"
        },
        score: {
          bsonType: "int",
          description: "Ranking score"
        },
        matched_triggers: {
          bsonType: "array",
          description: "Matched trigger keywords"
        },
        matched_support: {
          bsonType: "array",
          description: "Matched support keywords"
        },
        status: {
          enum: ["scraped", "qualified", "disqualified", "generated", "applied", "rejected", "interview", "error"],
          description: "Job processing status - required"
        },
        ranked_at: {
          bsonType: "date",
          description: "When job was ranked"
        },
        generated_at: {
          bsonType: "date",
          description: "When CV was generated"
        },
        applied_at: {
          bsonType: "date",
          description: "When application was submitted"
        },
        error: {
          bsonType: "string",
          description: "Error message if status is error"
        },
        created_at: {
          bsonType: "date",
          description: "Record creation timestamp"
        },
        updated_at: {
          bsonType: "date",
          description: "Record update timestamp"
        }
      }
    }
  },
  validationLevel: "moderate",
  validationAction: "warn"
});

print("Created jobs collection");

// Create indexes for jobs collection
db.jobs.createIndex({ linkedin_id: 1 }, { unique: true, name: "idx_linkedin_id" });
db.jobs.createIndex({ status: 1 }, { name: "idx_status" });
db.jobs.createIndex({ score: -1 }, { name: "idx_score" });
db.jobs.createIndex({ created_at: -1 }, { name: "idx_created_at" });
db.jobs.createIndex({ company: 1 }, { name: "idx_company" });
db.jobs.createIndex({ status: 1, score: -1 }, { name: "idx_status_score" });

print("Created indexes for jobs collection");

// Create applications collection
db.createCollection("applications", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["job_id", "status"],
      properties: {
        job_id: {
          bsonType: "string",
          description: "Reference to job - required"
        },
        job_title: {
          bsonType: "string",
          description: "Job title (denormalized)"
        },
        company: {
          bsonType: "string",
          description: "Company name (denormalized)"
        },
        resume_path: {
          bsonType: "string",
          description: "Path to generated resume PDF"
        },
        cover_letter_path: {
          bsonType: "string",
          description: "Path to generated cover letter PDF"
        },
        resume_content: {
          bsonType: "string",
          description: "Resume content in markdown"
        },
        cover_letter_content: {
          bsonType: "string",
          description: "Cover letter content"
        },
        status: {
          enum: ["pending", "submitted", "failed", "withdrawn"],
          description: "Application status - required"
        },
        submitted_at: {
          bsonType: "date",
          description: "When application was submitted"
        },
        response_received_at: {
          bsonType: "date",
          description: "When response was received"
        },
        notes: {
          bsonType: "string",
          description: "Additional notes"
        },
        created_at: {
          bsonType: "date",
          description: "Record creation timestamp"
        },
        updated_at: {
          bsonType: "date",
          description: "Record update timestamp"
        }
      }
    }
  },
  validationLevel: "moderate",
  validationAction: "warn"
});

print("Created applications collection");

// Create indexes for applications collection
db.applications.createIndex({ job_id: 1 }, { name: "idx_job_id" });
db.applications.createIndex({ status: 1 }, { name: "idx_status" });
db.applications.createIndex({ created_at: -1 }, { name: "idx_created_at" });

print("Created indexes for applications collection");

// Show collections
print("\nCollections in job_application database:");
db.getCollectionNames().forEach(function(collection) {
  print("  - " + collection);
});

// Show indexes
print("\nIndexes on jobs collection:");
db.jobs.getIndexes().forEach(function(idx) {
  print("  - " + idx.name + ": " + JSON.stringify(idx.key));
});

print("\nIndexes on applications collection:");
db.applications.getIndexes().forEach(function(idx) {
  print("  - " + idx.name + ": " + JSON.stringify(idx.key));
});

print("\nMongoDB initialization complete!");
