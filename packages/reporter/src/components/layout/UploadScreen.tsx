import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileJson, Database } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

interface UploadScreenProps {
  onLoadFile: (file: File) => void
  onLoadSample: () => void
  loading: boolean
  error: string | null
}

export function UploadScreen({ onLoadFile, onLoadSample, loading, error }: UploadScreenProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        onLoadFile(acceptedFiles[0])
      }
    },
    [onLoadFile],
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/json': ['.json'] },
    maxFiles: 1,
    disabled: loading,
  })

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="max-w-lg w-full space-y-6">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            LLM Spec Test Report
          </h1>
          <p className="text-slate-500">
            Upload a test-report.json file to view the results
          </p>
        </div>

        <Card
          {...getRootProps()}
          className={`p-12 border-2 border-dashed cursor-pointer transition-colors ${
            isDragActive
              ? 'border-blue-400 bg-blue-50'
              : 'border-slate-300 hover:border-blue-300 hover:bg-slate-50'
          } ${loading ? 'opacity-50 pointer-events-none' : ''}`}
        >
          <input {...getInputProps()} className="hidden" />
          <div className="flex flex-col items-center gap-4 text-center">
            {isDragActive ? (
              <>
                <Upload className="w-12 h-12 text-blue-500" />
                <p className="text-lg font-medium text-blue-600">Drop the file here</p>
              </>
            ) : (
              <>
                <FileJson className="w-12 h-12 text-slate-400" />
                <div className="space-y-1">
                  <p className="text-lg font-medium text-slate-700">
                    Drag & drop test-report.json
                  </p>
                  <p className="text-sm text-slate-500">or click to browse</p>
                </div>
              </>
            )}
          </div>
        </Card>

        {error && (
          <div className="p-4 bg-rose-50 border border-rose-200 rounded-lg text-sm text-rose-700">
            {error}
          </div>
        )}

        <div className="flex justify-center">
          <Button variant="outline" onClick={onLoadSample} disabled={loading}>
            <Database className="w-4 h-4 mr-2" />
            Load Demo Data
          </Button>
        </div>
      </div>
    </div>
  )
}
